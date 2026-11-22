# k6 summary

scenario: teacher_courses

- http_req_waiting: max=12.826, p(90)=12.124, p(95)=12.274, p(99)=12.716, avg=8.486, min=2.487, med=8.924
- http_req_duration: p(99)=12.948, avg=8.649, min=2.539, med=9.178, max=13.079, p(90)=12.325, p(95)=12.426
- iterations: count=20.000, rate=4.774
- http_req_connecting: max=0.073, p(90)=0.000, p(95)=0.004, p(99)=0.059, avg=0.004, min=0.000, med=0.000
- vus: min=1.000, max=1.000
- http_req_tls_handshaking: p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000
- http_req_receiving: min=0.031, med=0.109, max=0.463, p(90)=0.167, p(95)=0.291, p(99)=0.429, avg=0.124
- http_req_sending: med=0.040, max=0.100, p(90)=0.045, p(95)=0.055, p(99)=0.091, avg=0.039, min=0.012
- http_req_blocked: avg=0.014, min=0.003, med=0.011, max=0.099, p(90)=0.014, p(95)=0.021, p(99)=0.083
- http_req_failed: rate=0.000
- http_req_duration{expected_response:true}: p(95)=12.426, p(99)=12.948, avg=8.649, min=2.539, med=9.178, max=13.079, p(90)=12.325
