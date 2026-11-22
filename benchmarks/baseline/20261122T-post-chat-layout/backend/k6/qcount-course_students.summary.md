# k6 summary

scenario: course_students

- http_req_duration{expected_response:true}: avg=7.568, min=2.310, med=7.935, max=9.462, p(90)=9.204, p(95)=9.224, p(99)=9.414
- iterations: count=20.000, rate=4.793
- vus: min=1.000, max=1.000
- http_req_failed: rate=0.000
- http_req_duration: p(95)=9.224, p(99)=9.414, avg=7.568, min=2.310, med=7.935, max=9.462, p(90)=9.204
- http_req_blocked: p(95)=0.048, p(99)=0.122, avg=0.020, min=0.003, med=0.011, max=0.140, p(90)=0.027
- http_req_connecting: med=0.000, max=0.101, p(90)=0.000, p(95)=0.005, p(99)=0.082, avg=0.005, min=0.000
- http_req_receiving: max=0.236, p(90)=0.220, p(95)=0.235, p(99)=0.236, avg=0.139, min=0.031, med=0.134
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_sending: avg=0.044, min=0.015, med=0.042, max=0.071, p(90)=0.058, p(95)=0.063, p(99)=0.069
- http_req_waiting: p(95)=9.042, p(99)=9.241, avg=7.385, min=2.264, med=7.800, max=9.290, p(90)=8.947
