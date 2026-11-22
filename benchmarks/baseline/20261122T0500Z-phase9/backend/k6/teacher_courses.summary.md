# k6 summary

scenario: teacher_courses

- http_req_failed: rate=0.000
- vus: min=2.000, max=2.000
- http_req_receiving: p(95)=0.272, p(99)=0.324, avg=0.123, min=0.025, med=0.118, max=0.391, p(90)=0.219
- http_req_connecting: max=0.079, p(90)=0.000, p(95)=0.000, p(99)=0.073, avg=0.002, min=0.000, med=0.000
- http_req_duration{expected_response:true}: p(90)=13.104, p(95)=13.817, p(99)=38.041, avg=9.691, min=2.633, med=9.255, max=38.695
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_duration: p(99)=38.041, avg=9.691, min=2.633, med=9.255, max=38.695, p(90)=13.104, p(95)=13.817
- iterations: count=96.000, rate=9.494
- http_req_waiting: max=38.602, p(90)=12.938, p(95)=13.661, p(99)=37.919, avg=9.526, min=2.576, med=9.028
- http_req_sending: avg=0.041, min=0.010, med=0.040, max=0.150, p(90)=0.051, p(95)=0.064, p(99)=0.086
- http_req_blocked: avg=0.012, min=0.002, med=0.011, max=0.109, p(90)=0.014, p(95)=0.016, p(99)=0.096
