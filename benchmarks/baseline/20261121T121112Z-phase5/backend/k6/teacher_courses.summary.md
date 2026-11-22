# k6 summary

scenario: teacher_courses

- http_req_failed: rate=0.000
- vus: min=2.000, max=2.000
- http_req_connecting: max=0.107, p(90)=0.000, p(95)=0.000, p(99)=0.091, avg=0.002, min=0.000, med=0.000
- http_req_tls_handshaking: max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000
- http_req_sending: min=0.012, med=0.043, max=0.128, p(90)=0.051, p(95)=0.064, p(99)=0.089, avg=0.043
- iterations: count=86.000, rate=8.417
- http_req_waiting: p(99)=51.733, avg=36.679, min=18.194, med=36.151, max=51.837, p(90)=47.579, p(95)=49.510
- http_req_duration{expected_response:true}: avg=36.776, min=18.259, med=36.252, max=51.976, p(90)=47.661, p(95)=49.610, p(99)=51.858
- http_req_blocked: p(90)=0.021, p(95)=0.035, p(99)=0.123, avg=0.016, min=0.003, med=0.012, max=0.139
- http_req_duration: avg=36.776, min=18.259, med=36.252, max=51.976, p(90)=47.661, p(95)=49.610, p(99)=51.858
- http_req_receiving: p(99)=0.122, avg=0.054, min=0.020, med=0.051, max=0.133, p(90)=0.079, p(95)=0.085
