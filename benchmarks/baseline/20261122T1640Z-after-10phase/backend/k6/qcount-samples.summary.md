# k6 summary

scenario: samples

- http_req_connecting: avg=0.051, min=0.000, med=0.000, max=1.021, p(90)=0.000, p(95)=0.051, p(99)=0.827
- http_req_blocked: avg=0.082, min=0.003, med=0.011, max=1.428, p(90)=0.013, p(95)=0.087, p(99)=1.160
- http_req_duration{expected_response:true}: avg=19.602, min=6.348, med=21.437, max=24.009, p(90)=23.538, p(95)=23.690, p(99)=23.945
- http_req_waiting: min=6.289, med=21.284, max=23.865, p(90)=23.364, p(95)=23.491, p(99)=23.790, avg=19.426
- iterations: count=20.000, rate=4.532
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- vus: min=1.000, max=1.000
- http_req_receiving: avg=0.128, min=0.038, med=0.118, max=0.262, p(90)=0.195, p(95)=0.234, p(99)=0.256
- http_req_sending: med=0.042, max=0.130, p(90)=0.054, p(95)=0.075, p(99)=0.119, avg=0.047, min=0.011
- http_req_failed: rate=0.000
- http_req_duration: p(90)=23.538, p(95)=23.690, p(99)=23.945, avg=19.602, min=6.348, med=21.437, max=24.009
