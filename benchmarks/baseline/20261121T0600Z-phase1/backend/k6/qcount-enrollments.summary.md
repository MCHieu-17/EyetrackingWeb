# k6 summary

scenario: enrollments

- http_req_receiving: max=0.351, p(90)=0.190, p(95)=0.199, p(99)=0.321, avg=0.126, min=0.028, med=0.117
- http_req_duration: avg=5.010, min=1.532, med=5.178, max=5.554, p(90)=5.489, p(95)=5.544, p(99)=5.552
- http_req_waiting: avg=4.841, min=1.486, med=4.961, max=5.399, p(90)=5.376, p(95)=5.380, p(99)=5.396
- http_req_sending: avg=0.043, min=0.012, med=0.041, max=0.087, p(90)=0.047, p(95)=0.055, p(99)=0.081
- iterations: count=20.000, rate=4.851
- http_req_duration{expected_response:true}: min=1.532, med=5.178, max=5.554, p(90)=5.489, p(95)=5.544, p(99)=5.552, avg=5.010
- http_req_blocked: max=0.104, p(90)=0.020, p(95)=0.048, p(99)=0.093, avg=0.018, min=0.003, med=0.011
- http_req_connecting: p(95)=0.004, p(99)=0.062, avg=0.004, min=0.000, med=0.000, max=0.077, p(90)=0.000
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- vus: min=1.000, max=1.000
- http_req_failed: rate=0.000
