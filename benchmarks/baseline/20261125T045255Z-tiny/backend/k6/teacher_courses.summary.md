# k6 summary

scenario: teacher_courses

- http_req_failed: rate=0.000
- http_req_duration: p(99)=13.995, avg=8.361, min=2.491, med=8.564, max=14.290, p(90)=11.757, p(95)=12.761
- http_req_sending: max=0.096, p(90)=0.054, p(95)=0.062, p(99)=0.076, avg=0.040, min=0.007, med=0.040
- http_req_receiving: p(90)=0.233, p(95)=0.288, p(99)=0.462, avg=0.131, min=0.021, med=0.118, max=0.742
- http_req_waiting: max=14.101, p(90)=11.548, p(95)=12.525, p(99)=13.718, avg=8.190, min=2.456, med=8.389
- iterations: count=96.000, rate=9.553
- http_req_duration{expected_response:true}: p(90)=11.757, p(95)=12.761, p(99)=13.995, avg=8.361, min=2.491, med=8.564, max=14.290
- vus: min=2.000, max=2.000
- http_req_blocked: avg=0.015, min=0.002, med=0.011, max=0.127, p(90)=0.014, p(95)=0.039, p(99)=0.115
- http_req_connecting: min=0.000, med=0.000, max=0.084, p(90)=0.000, p(95)=0.000, p(99)=0.082, avg=0.002
- http_req_tls_handshaking: p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000
