# k6 summary

scenario: course_students

- http_req_failed: rate=0.000
- http_req_waiting: max=34.106, p(90)=11.127, p(95)=12.822, p(99)=29.849, avg=9.875, min=5.026, med=9.232
- vus: min=1.000, max=1.000
- http_req_duration{expected_response:true}: avg=10.165, min=5.544, med=9.563, max=34.259, p(90)=11.410, p(95)=13.073, p(99)=30.022
- http_req_receiving: max=1.145, p(90)=0.356, p(95)=0.506, p(99)=1.017, avg=0.244, min=0.034, med=0.206
- http_req_connecting: med=0.000, max=0.130, p(90)=0.000, p(95)=0.007, p(99)=0.105, avg=0.007, min=0.000
- http_req_sending: med=0.044, max=0.076, p(90)=0.049, p(95)=0.054, p(99)=0.071, avg=0.045, min=0.027
- http_req_duration: avg=10.165, min=5.544, med=9.563, max=34.259, p(90)=11.410, p(95)=13.073, p(99)=30.022
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_blocked: avg=0.021, min=0.007, med=0.011, max=0.177, p(90)=0.020, p(95)=0.032, p(99)=0.148
- iterations: count=20.000, rate=4.735
