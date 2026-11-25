# k6 summary

scenario: teacher_courses

- vus: min=1.000, max=1.000
- http_req_duration: p(99)=12.632, avg=9.167, min=2.557, med=9.299, max=12.646, p(90)=12.375, p(95)=12.574
- http_req_waiting: p(90)=12.122, p(95)=12.376, p(99)=12.395, avg=8.989, min=2.509, med=9.111, max=12.399
- http_req_blocked: max=0.136, p(90)=0.017, p(95)=0.039, p(99)=0.116, avg=0.018, min=0.003, med=0.011
- http_req_connecting: p(90)=0.000, p(95)=0.005, p(99)=0.079, avg=0.005, min=0.000, med=0.000, max=0.098
- http_req_sending: max=0.060, p(90)=0.053, p(95)=0.058, p(99)=0.060, avg=0.041, min=0.011, med=0.040
- http_req_receiving: avg=0.137, min=0.027, med=0.137, max=0.265, p(90)=0.212, p(95)=0.234, p(99)=0.258
- iterations: count=20.000, rate=4.752
- http_req_failed: rate=0.000
- http_req_duration{expected_response:true}: p(95)=12.574, p(99)=12.632, avg=9.167, min=2.557, med=9.299, max=12.646, p(90)=12.375
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
