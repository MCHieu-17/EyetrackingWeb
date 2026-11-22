# k6 summary

scenario: teacher_courses

- http_req_receiving: p(99)=0.284, avg=0.114, min=0.033, med=0.110, max=0.289, p(90)=0.177, p(95)=0.265
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_failed: rate=0.000
- http_req_duration{expected_response:true}: p(99)=20.000, avg=9.147, min=2.570, med=8.185, max=21.569, p(90)=12.721, p(95)=13.728
- http_req_blocked: max=0.131, p(90)=0.018, p(95)=0.054, p(99)=0.116, avg=0.018, min=0.004, med=0.011
- http_req_waiting: p(99)=19.790, avg=8.987, min=2.515, med=8.000, max=21.342, p(90)=12.579, p(95)=13.579
- vus: min=1.000, max=1.000
- http_req_sending: p(99)=0.156, avg=0.046, min=0.013, med=0.042, max=0.180, p(90)=0.053, p(95)=0.061
- http_req_duration: p(95)=13.728, p(99)=20.000, avg=9.147, min=2.570, med=8.185, max=21.569, p(90)=12.721
- iterations: count=20.000, rate=4.760
- http_req_connecting: min=0.000, med=0.000, max=0.074, p(90)=0.000, p(95)=0.004, p(99)=0.060, avg=0.004
