# k6 summary

scenario: course_students

- http_req_connecting: min=0.000, med=0.000, max=0.079, p(90)=0.000, p(95)=0.004, p(99)=0.064, avg=0.004
- http_req_sending: p(95)=0.060, p(99)=0.065, avg=0.040, min=0.012, med=0.044, max=0.066, p(90)=0.055
- http_req_duration{expected_response:true}: min=33.896, med=59.995, max=100.131, p(90)=90.830, p(95)=94.777, p(99)=99.060, avg=61.754
- iterations: count=20.000, rate=3.806
- vus: min=1.000, max=1.000
- http_req_duration: avg=61.754, min=33.896, med=59.995, max=100.131, p(90)=90.830, p(95)=94.777, p(99)=99.060
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_receiving: max=1.001, p(90)=0.420, p(95)=0.502, p(99)=0.901, avg=0.244, min=0.094, med=0.181
- http_req_waiting: max=99.918, p(90)=90.575, p(95)=94.592, p(99)=98.852, avg=61.471, min=33.689, med=59.780
- http_req_blocked: avg=0.015, min=0.003, med=0.012, max=0.108, p(90)=0.013, p(95)=0.017, p(99)=0.090
- http_req_failed: rate=0.000
