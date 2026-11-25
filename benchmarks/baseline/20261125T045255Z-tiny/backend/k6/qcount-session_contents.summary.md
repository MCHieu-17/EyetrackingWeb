# k6 summary

scenario: session_contents

- http_req_waiting: p(95)=14.943, p(99)=15.630, avg=11.149, min=3.443, med=12.188, max=15.801, p(90)=14.216
- http_req_duration{expected_response:true}: avg=11.342, min=3.500, med=12.403, max=16.124, p(90)=14.379, p(95)=15.111, p(99)=15.922
- http_req_receiving: avg=0.148, min=0.026, med=0.130, max=0.314, p(90)=0.239, p(95)=0.282, p(99)=0.308
- http_req_sending: p(95)=0.063, p(99)=0.091, avg=0.045, min=0.012, med=0.043, max=0.098, p(90)=0.056
- vus: min=1.000, max=1.000
- http_req_failed: rate=0.000
- iterations: count=20.000, rate=4.705
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- http_req_connecting: avg=0.003, min=0.000, med=0.000, max=0.069, p(90)=0.000, p(95)=0.003, p(99)=0.056
- http_req_blocked: p(95)=0.054, p(99)=0.086, avg=0.018, min=0.004, med=0.011, max=0.094, p(90)=0.029
- http_req_duration: max=16.124, p(90)=14.379, p(95)=15.111, p(99)=15.922, avg=11.342, min=3.500, med=12.403
