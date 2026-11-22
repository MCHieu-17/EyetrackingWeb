# k6 summary

scenario: teacher_courses

- http_req_failed: rate=0.000
- http_req_connecting: min=0.000, med=0.000, max=0.125, p(90)=0.000, p(95)=0.006, p(99)=0.101, avg=0.006
- http_req_duration{expected_response:true}: max=45.571, p(90)=44.613, p(95)=45.547, p(99)=45.566, avg=36.030, min=18.854, med=37.399
- http_req_blocked: avg=0.020, min=0.003, med=0.011, max=0.181, p(90)=0.015, p(95)=0.031, p(99)=0.151
- http_req_duration: avg=36.030, min=18.854, med=37.399, max=45.571, p(90)=44.613, p(95)=45.547, p(99)=45.566
- http_req_receiving: p(95)=0.057, p(99)=0.065, avg=0.040, min=0.027, med=0.039, max=0.067, p(90)=0.047
- iterations: count=20.000, rate=4.218
- http_req_sending: min=0.012, med=0.043, max=0.057, p(90)=0.051, p(95)=0.053, p(99)=0.056, avg=0.043
- vus: min=1.000, max=1.000
- http_req_waiting: p(99)=45.476, avg=35.947, min=18.801, med=37.324, max=45.480, p(90)=44.529, p(95)=45.460
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
