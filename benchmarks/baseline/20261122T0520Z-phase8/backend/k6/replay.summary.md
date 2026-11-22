# k6 summary

scenario: replay

- iterations: count=88.000, rate=8.619
- http_req_duration: avg=31.101, min=13.042, med=29.428, max=90.056, p(90)=47.014, p(95)=48.228, p(99)=68.327
- http_req_receiving: avg=0.140, min=0.047, med=0.106, max=0.579, p(90)=0.264, p(95)=0.357, p(99)=0.575
- http_req_failed: rate=0.000
- http_req_blocked: min=0.003, med=0.011, max=0.122, p(90)=0.015, p(95)=0.027, p(99)=0.106, avg=0.015
- http_req_duration{expected_response:true}: p(90)=47.014, p(95)=48.228, p(99)=68.327, avg=31.101, min=13.042, med=29.428, max=90.056
- http_req_connecting: avg=0.002, min=0.000, med=0.000, max=0.073, p(90)=0.000, p(95)=0.000, p(99)=0.070
- vus: max=2.000, min=2.000
- http_req_sending: p(90)=0.051, p(95)=0.060, p(99)=0.075, avg=0.041, min=0.008, med=0.042, max=0.076
- http_req_waiting: p(90)=46.841, p(95)=47.997, p(99)=68.186, avg=30.920, min=12.928, med=29.294, max=89.945
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
