# k6 summary

scenario: enrollments

- iterations: count=245.000, rate=24.039
- http_req_receiving: max=1.484, p(90)=0.226, p(95)=0.313, p(99)=0.625, avg=0.123, min=0.009, med=0.105
- http_req_duration{expected_response:true}: avg=6.652, min=1.001, med=5.727, max=66.859, p(90)=7.232, p(95)=7.918, p(99)=56.690
- http_req_waiting: avg=6.485, min=0.930, med=5.641, max=66.542, p(90)=7.039, p(95)=7.593, p(99)=56.340
- http_req_connecting: med=0.000, max=0.217, p(90)=0.000, p(95)=0.000, p(99)=0.214, avg=0.004, min=0.000
- http_req_failed: rate=0.000
- http_req_duration: avg=6.652, min=1.001, med=5.727, max=66.859, p(90)=7.232, p(95)=7.918, p(99)=56.690
- http_req_sending: p(95)=0.061, p(99)=0.298, avg=0.044, min=0.005, med=0.038, max=0.509, p(90)=0.049
- http_req_blocked: p(95)=0.020, p(99)=0.642, avg=0.025, min=0.002, med=0.011, max=0.676, p(90)=0.015
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- vus: min=5.000, max=5.000
