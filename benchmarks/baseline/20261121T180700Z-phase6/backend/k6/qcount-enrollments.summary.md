# k6 summary

scenario: enrollments

- http_req_blocked: min=0.005, med=0.011, max=0.436, p(90)=0.045, p(95)=0.124, p(99)=0.373, avg=0.038
- vus: min=1.000, max=1.000
- iterations: count=20.000, rate=4.877
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_duration{expected_response:true}: med=4.220, max=4.938, p(90)=4.419, p(95)=4.460, p(99)=4.843, avg=3.971, min=1.070
- http_req_receiving: p(95)=0.161, p(99)=0.167, avg=0.113, min=0.035, med=0.118, max=0.169, p(90)=0.149
- http_req_sending: min=0.012, med=0.041, max=0.083, p(90)=0.050, p(95)=0.056, p(99)=0.078, avg=0.042
- http_req_duration: min=1.070, med=4.220, max=4.938, p(90)=4.419, p(95)=4.460, p(99)=4.843, avg=3.971
- http_req_waiting: p(99)=4.666, avg=3.816, min=1.023, med=4.081, max=4.757, p(90)=4.250, p(95)=4.305
- http_req_failed: rate=0.000
- http_req_connecting: p(99)=0.063, avg=0.004, min=0.000, med=0.000, max=0.077, p(90)=0.000, p(95)=0.004
