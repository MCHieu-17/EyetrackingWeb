# k6 summary

scenario: outline

- http_req_connecting: p(90)=0.000, p(95)=0.000, p(99)=0.099, avg=0.002, min=0.000, med=0.000, max=0.101
- http_req_duration{expected_response:true}: med=7.348, max=15.530, p(90)=12.295, p(95)=12.829, p(99)=14.097, avg=8.174, min=2.027
- vus: min=5.000, max=5.000
- http_req_tls_handshaking: p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000
- http_req_receiving: max=0.928, p(90)=0.277, p(95)=0.373, p(99)=0.539, avg=0.126, min=0.015, med=0.069
- http_req_failed: rate=0.000
- http_req_blocked: p(95)=0.026, p(99)=0.126, avg=0.014, min=0.002, med=0.011, max=0.129, p(90)=0.015
- http_req_sending: p(95)=0.066, p(99)=0.082, avg=0.042, min=0.005, med=0.041, max=0.305, p(90)=0.051
- http_req_duration: max=15.530, p(90)=12.295, p(95)=12.829, p(99)=14.097, avg=8.174, min=2.027, med=7.348
- iterations: rate=23.866, count=243.000
- http_req_waiting: avg=8.006, min=1.972, med=7.268, max=15.094, p(90)=12.081, p(95)=12.639, p(99)=13.968
