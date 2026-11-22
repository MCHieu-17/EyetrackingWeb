# k6 summary

scenario: teacher_courses

- http_req_blocked: p(99)=0.110, avg=0.020, min=0.004, med=0.011, max=0.117, p(90)=0.025, p(95)=0.082
- http_req_waiting: avg=9.358, min=2.605, med=9.299, max=13.458, p(90)=13.089, p(95)=13.436, p(99)=13.453
- http_req_duration{expected_response:true}: p(90)=13.258, p(95)=13.535, p(99)=13.692, avg=9.521, min=2.651, med=9.583, max=13.731
- vus: min=1.000, max=1.000
- http_req_duration: avg=9.521, min=2.651, med=9.583, max=13.731, p(90)=13.258, p(95)=13.535, p(99)=13.692
- http_req_receiving: max=0.358, p(90)=0.213, p(95)=0.325, p(99)=0.352, avg=0.120, min=0.030, med=0.112
- http_req_sending: avg=0.044, min=0.013, med=0.042, max=0.073, p(90)=0.063, p(95)=0.068, p(99)=0.072
- http_req_connecting: p(90)=0.000, p(95)=0.004, p(99)=0.070, avg=0.004, min=0.000, med=0.000, max=0.087
- iterations: count=20.000, rate=4.749
- http_req_tls_handshaking: max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000
- http_req_failed: rate=0.000
