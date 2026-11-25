"""Thư viện convert các model TFLite của MediaPipe FaceLandmarker sang ONNX (chỉ chạy ở image export).

Chỉ hỗ trợ tập op có trong `face_detector.tflite` và `face_landmarks_detector.tflite`:
CONV_2D, DEPTHWISE_CONV_2D, PRELU, RELU, ADD, PAD, MAX_POOL_2D, LOGISTIC, RESHAPE,
CONCATENATION và DEQUANTIZE (hằng số fp16 -> fp32). Op khác -> báo lỗi rõ ràng.

Layout: đầu vào NHWC (như TFLite) được chuyển sang NCHW một lần; mọi tensor 4 chiều
trong graph là NCHW; trước RESHAPE và ở output sẽ chuyển lại NHWC để khớp TFLite.
Batch động (dim 0) để gộp nhiều frame.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import onnx
import tflite
from onnx import TensorProto, helper, numpy_helper

OPS = {
    v: k for k, v in vars(tflite.BuiltinOperator).items() if not k.startswith("_")
}
SAME, VALID = 0, 1
ACT_NONE, ACT_RELU, ACT_RELU6 = 0, 1, 3


def _options(op, cls):
    options = cls()
    options.Init(op.BuiltinOptions().Bytes, op.BuiltinOptions().Pos)
    return options


class Converter:
    def __init__(self, data: bytes, name: str):
        self.model = tflite.Model.GetRootAsModel(data, 0)
        self.graph = self.model.Subgraphs(0)
        self.name = name
        self.nodes: list = []
        self.inits: list = []
        self.consts: dict[int, np.ndarray] = {}
        self.names: dict[int, str] = {}
        self.ndim: dict[int, int] = {}
        self._uid = 0

    # --- helpers -------------------------------------------------------
    def _tmp(self, base: str) -> str:
        self._uid += 1
        return f"{base}_{self._uid}"

    def _tensor(self, index: int):
        return self.graph.Tensors(index)

    def _shape(self, index: int) -> list[int]:
        tensor = self._tensor(index)
        return [int(x) for x in tensor.ShapeAsNumpy()] if tensor.ShapeLength() else []

    def _const(self, index: int) -> np.ndarray | None:
        if index in self.consts:
            return self.consts[index]
        tensor = self._tensor(index)
        buffer = self.model.Buffers(tensor.Buffer())
        if buffer.DataLength() == 0:
            return None
        dtype = {0: np.float32, 1: np.float16, 2: np.int32}[tensor.Type()]
        array = np.frombuffer(buffer.DataAsNumpy().tobytes(), dtype=dtype)
        array = array.reshape(self._shape(index))
        self.consts[index] = array
        return array

    def _name(self, index: int) -> str:
        if index not in self.names:
            self.names[index] = f"t{index}"
        return self.names[index]

    def _add_init(self, name: str, array: np.ndarray) -> str:
        self.inits.append(numpy_helper.from_array(array, name))
        return name

    def _transpose(self, source: str, perm: list[int]) -> str:
        out = self._tmp("tr")
        self.nodes.append(helper.make_node("Transpose", [source], [out], perm=perm))
        return out

    def _activation(self, source: str, act: int) -> str:
        if act == ACT_NONE:
            return source
        out = self._tmp("act")
        if act == ACT_RELU:
            self.nodes.append(helper.make_node("Relu", [source], [out]))
        elif act == ACT_RELU6:
            self.nodes.append(helper.make_node("Clip", [source], [out], min=0.0, max=6.0))
        else:
            raise NotImplementedError(f"fused activation {act}")
        return out

    # --- ops -------------------------------------------------------------
    def _conv(self, op, ins, outs, depthwise: bool):
        cls = tflite.DepthwiseConv2DOptions if depthwise else tflite.Conv2DOptions
        options = _options(op, cls)
        if options.DilationHFactor() != 1 or options.DilationWFactor() != 1:
            raise NotImplementedError("dilation")
        weight = self._const(ins[1]).astype(np.float32)
        bias = self._const(ins[2]).astype(np.float32)
        if depthwise:
            channels = weight.shape[3]
            kernel = np.transpose(weight, (3, 0, 1, 2)).copy()  # [C*m,1,H,W]
            group = channels // options.DepthMultiplier()
        else:
            kernel = np.transpose(weight, (0, 3, 1, 2)).copy()  # OHWI -> OIHW
            group = 1
        w_name = self._add_init(self._tmp("w"), kernel)
        b_name = self._add_init(self._tmp("b"), bias)
        attrs = dict(
            strides=[options.StrideH(), options.StrideW()],
            group=group,
            kernel_shape=[kernel.shape[2], kernel.shape[3]],
        )
        if options.Padding() == SAME:
            attrs["auto_pad"] = "SAME_UPPER"
        elif options.Padding() != VALID:
            raise NotImplementedError("padding")
        out = self._tmp("conv")
        self.nodes.append(
            helper.make_node(
                "Conv", [self._name(ins[0]), w_name, b_name], [out], **attrs
            )
        )
        self.names[outs[0]] = self._activation(out, options.FusedActivationFunction())

    def _prelu(self, ins, outs):
        alpha = self._const(ins[1]).astype(np.float32)
        slope = np.transpose(alpha.reshape(alpha.shape[-3:]), (2, 0, 1)).copy()
        s_name = self._add_init(self._tmp("slope"), slope)
        out = self._tmp("prelu")
        self.nodes.append(
            helper.make_node("PRelu", [self._name(ins[0]), s_name], [out])
        )
        self.names[outs[0]] = out

    def _pad(self, ins, outs):
        pads = self._const(ins[1]).astype(np.int64)  # [4,2] NHWC (begin,end)
        nchw = pads[[0, 3, 1, 2]]
        values = np.concatenate([nchw[:, 0], nchw[:, 1]]).astype(np.int64)
        p_name = self._add_init(self._tmp("pads"), values)
        out = self._tmp("pad")
        self.nodes.append(
            helper.make_node("Pad", [self._name(ins[0]), p_name], [out], mode="constant")
        )
        self.names[outs[0]] = out

    def _max_pool(self, op, ins, outs):
        options = _options(op, tflite.Pool2DOptions)
        attrs = dict(
            kernel_shape=[options.FilterHeight(), options.FilterWidth()],
            strides=[options.StrideH(), options.StrideW()],
        )
        if options.Padding() == SAME:
            attrs["auto_pad"] = "SAME_UPPER"
        out = self._tmp("pool")
        self.nodes.append(helper.make_node("MaxPool", [self._name(ins[0])], [out], **attrs))
        self.names[outs[0]] = self._activation(out, options.FusedActivationFunction())

    def _add(self, op, ins, outs):
        out = self._tmp("add")
        self.nodes.append(
            helper.make_node("Add", [self._name(ins[0]), self._name(ins[1])], [out])
        )
        act = ACT_NONE
        if op.BuiltinOptions() is not None:
            act = _options(op, tflite.AddOptions).FusedActivationFunction()
        self.names[outs[0]] = self._activation(out, act)

    def _reshape(self, ins, outs):
        source = self._name(ins[0])
        if len(self._shape(ins[0])) == 4:
            source = self._transpose(source, [0, 2, 3, 1])
        target = self._shape(outs[0])
        target[0] = -1
        s_name = self._add_init(self._tmp("shape"), np.array(target, dtype=np.int64))
        out = self._tmp("reshape")
        self.nodes.append(helper.make_node("Reshape", [source, s_name], [out]))
        self.names[outs[0]] = out

    def _concat(self, op, ins, outs):
        options = _options(op, tflite.ConcatenationOptions)
        rank = len(self._shape(ins[0]))
        if rank != 3 or options.Axis() not in (1, -2):
            raise NotImplementedError("concat chỉ hỗ trợ rank 3 trục 1")
        out = self._tmp("cat")
        self.nodes.append(
            helper.make_node("Concat", [self._name(i) for i in ins], [out], axis=1)
        )
        self.names[outs[0]] = out

    # --- build -----------------------------------------------------------
    def convert(self) -> onnx.ModelProto:
        graph = self.graph
        in_index = graph.Inputs(0)
        in_shape = self._shape(in_index)
        self.names[in_index] = self._transpose("input", [0, 3, 1, 2])

        dequant = {}
        for i in range(graph.OperatorsLength()):
            op = graph.Operators(i)
            code = self.model.OperatorCodes(op.OpcodeIndex())
            kind = OPS[max(code.BuiltinCode(), code.DeprecatedBuiltinCode())]
            ins = [op.Inputs(j) for j in range(op.InputsLength())]
            outs = [op.Outputs(j) for j in range(op.OutputsLength())]
            if kind == "DEQUANTIZE":
                dequant[outs[0]] = self._const(ins[0]).astype(np.float32)
                self.consts[outs[0]] = dequant[outs[0]]
            elif kind == "CONV_2D":
                self._conv(op, ins, outs, depthwise=False)
            elif kind == "DEPTHWISE_CONV_2D":
                self._conv(op, ins, outs, depthwise=True)
            elif kind == "PRELU":
                self._prelu(ins, outs)
            elif kind == "RELU":
                out = self._tmp("relu")
                self.nodes.append(helper.make_node("Relu", [self._name(ins[0])], [out]))
                self.names[outs[0]] = out
            elif kind == "ADD":
                self._add(op, ins, outs)
            elif kind == "PAD":
                self._pad(ins, outs)
            elif kind == "MAX_POOL_2D":
                self._max_pool(op, ins, outs)
            elif kind == "LOGISTIC":
                out = self._tmp("sig")
                self.nodes.append(helper.make_node("Sigmoid", [self._name(ins[0])], [out]))
                self.names[outs[0]] = out
            elif kind == "RESHAPE":
                self._reshape(ins, outs)
            elif kind == "CONCATENATION":
                self._concat(op, ins, outs)
            else:
                raise NotImplementedError(f"op TFLite chưa hỗ trợ: {kind}")

        outputs = []
        for j in range(graph.OutputsLength()):
            index = graph.Outputs(j)
            source = self._name(index)
            shape = self._shape(index)
            if len(shape) == 4:
                source = self._transpose(source, [0, 2, 3, 1])
            final = f"out{j}"
            self.nodes.append(helper.make_node("Identity", [source], [final]))
            dims = ["N", *shape[1:]]
            outputs.append(helper.make_tensor_value_info(final, TensorProto.FLOAT, dims))

        graph_proto = helper.make_graph(
            self.nodes,
            self.name,
            [helper.make_tensor_value_info("input", TensorProto.FLOAT, ["N", *in_shape[1:]])],
            outputs,
            self.inits,
        )
        model = helper.make_model(
            graph_proto, opset_imports=[helper.make_opsetid("", 17)]
        )
        model.ir_version = 9
        onnx.checker.check_model(model)
        return model


def convert_file(path: Path, name: str) -> onnx.ModelProto:
    return Converter(path.read_bytes(), name).convert()


def extract_task(task: Path, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {}
    with zipfile.ZipFile(task) as archive:
        for member in ("face_detector.tflite", "face_landmarks_detector.tflite"):
            target = out_dir / member
            target.write_bytes(archive.read(member))
            result[member] = target
    return result
