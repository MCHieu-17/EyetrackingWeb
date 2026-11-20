# k6 summary

scenario: aoi_summary

- http_req_waiting: avg=1205.472, min=1110.513, med=1200.112, max=1259.523, p(90)=1249.292, p(95)=1250.336, p(99)=1257.686
- http_req_failed: rate=0.000
- http_req_receiving: p(95)=0.962, p(99)=1.008, avg=0.344, min=0.161, med=0.238, max=1.020, p(90)=0.648
- http_req_connecting: p(99)=0.060, avg=0.004, min=0.000, med=0.000, max=0.074, p(90)=0.000, p(95)=0.004
- vus: min=1.000, max=1.000
- http_req_duration: avg=1205.880, min=1110.744, med=1200.413, max=1259.767, p(90)=1249.585, p(95)=1250.998, p(99)=1258.013
- iterations: count=20.000, rate=0.711
- http_req_duration{expected_response:true}: p(95)=1250.998, p(99)=1258.013, avg=1205.880, min=1110.744, med=1200.413, max=1259.767, p(90)=1249.585
- http_req_blocked: med=0.011, max=0.105, p(90)=0.015, p(95)=0.022, p(99)=0.089, avg=0.016, min=0.003
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_sending: p(90)=0.079, p(95)=0.105, p(99)=0.170, avg=0.064, min=0.023, med=0.056, max=0.187
