# k6 summary

scenario: enrollments

- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- vus: min=1.000, max=1.000
- http_req_connecting: avg=0.005, min=0.000, med=0.000, max=0.105, p(90)=0.000, p(95)=0.005, p(99)=0.085
- http_req_duration{expected_response:true}: avg=4.981, min=1.374, med=5.044, max=6.891, p(90)=5.279, p(95)=5.921, p(99)=6.697
- http_req_blocked: max=0.157, p(90)=0.014, p(95)=0.027, p(99)=0.131, avg=0.019, min=0.003, med=0.011
- http_req_receiving: p(99)=0.459, avg=0.164, min=0.031, med=0.137, max=0.494, p(90)=0.231, p(95)=0.318
- http_req_failed: rate=0.000
- http_req_waiting: p(99)=6.511, avg=4.774, min=1.333, med=4.865, max=6.743, p(90)=5.038, p(95)=5.582
- http_req_sending: min=0.010, med=0.041, max=0.075, p(90)=0.050, p(95)=0.059, p(99)=0.072, avg=0.043
- iterations: count=20.000, rate=4.853
- http_req_duration: p(99)=6.697, avg=4.981, min=1.374, med=5.044, max=6.891, p(90)=5.279, p(95)=5.921
