# k6 summary

scenario: course_students

- http_req_duration: min=1.765, med=7.808, max=16.522, p(90)=11.568, p(95)=11.776, p(99)=13.563, avg=8.028
- http_req_connecting: min=0.000, med=0.000, max=0.087, p(90)=0.000, p(95)=0.000, p(99)=0.067, avg=0.001
- http_req_receiving: avg=0.167, min=0.016, med=0.125, max=0.834, p(90)=0.363, p(95)=0.431, p(99)=0.623
- http_req_failed: rate=0.000
- http_req_sending: p(99)=0.081, avg=0.043, min=0.004, med=0.040, max=0.788, p(90)=0.051, p(95)=0.058
- http_req_duration{expected_response:true}: max=16.522, p(90)=11.568, p(95)=11.776, p(99)=13.563, avg=8.028, min=1.765, med=7.808
- http_req_blocked: max=0.324, p(90)=0.014, p(95)=0.016, p(99)=0.104, avg=0.014, min=0.001, med=0.011
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- iterations: count=243.000, rate=23.857
- http_req_waiting: min=1.713, med=7.572, max=16.433, p(90)=11.143, p(95)=11.527, p(99)=13.453, avg=7.818
- vus: min=5.000, max=5.000
