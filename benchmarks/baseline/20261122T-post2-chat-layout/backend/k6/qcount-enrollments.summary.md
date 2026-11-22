# k6 summary

scenario: enrollments

- http_req_receiving: avg=0.117, min=0.036, med=0.125, max=0.178, p(90)=0.154, p(95)=0.157, p(99)=0.174
- http_req_connecting: p(95)=0.004, p(99)=0.066, avg=0.004, min=0.000, med=0.000, max=0.082, p(90)=0.000
- iterations: count=20.000, rate=4.876
- http_req_failed: rate=0.000
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_duration{expected_response:true}: avg=3.985, min=1.101, med=4.351, max=4.522, p(90)=4.476, p(95)=4.482, p(99)=4.514
- http_req_sending: med=0.041, max=0.083, p(90)=0.048, p(95)=0.053, p(99)=0.077, avg=0.040, min=0.012
- http_req_blocked: max=0.110, p(90)=0.012, p(95)=0.018, p(99)=0.092, avg=0.015, min=0.003, med=0.011
- http_req_waiting: p(95)=4.301, p(99)=4.334, avg=3.828, min=1.047, med=4.172, max=4.342, p(90)=4.293
- vus: min=1.000, max=1.000
- http_req_duration: p(95)=4.482, p(99)=4.514, avg=3.985, min=1.101, med=4.351, max=4.522, p(90)=4.476
