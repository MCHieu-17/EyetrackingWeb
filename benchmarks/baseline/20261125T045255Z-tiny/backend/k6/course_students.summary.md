# k6 summary

scenario: course_students

- http_req_connecting: p(90)=0.000, p(95)=0.000, p(99)=0.078, avg=0.002, min=0.000, med=0.000, max=0.093
- http_req_sending: p(90)=0.051, p(95)=0.063, p(99)=0.104, avg=0.043, min=0.006, med=0.040, max=0.679
- iterations: count=243.000, rate=23.876
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_waiting: max=15.609, p(90)=11.401, p(95)=11.760, p(99)=14.241, avg=7.704, min=1.710, med=7.412
- vus: min=5.000, max=5.000
- http_req_failed: rate=0.000
- http_req_duration{expected_response:true}: avg=7.894, min=1.750, med=7.616, max=15.685, p(90)=11.616, p(95)=11.997, p(99)=14.351
- http_req_receiving: p(95)=0.353, p(99)=0.590, avg=0.147, min=0.009, med=0.109, max=1.182, p(90)=0.314
- http_req_blocked: p(99)=0.111, avg=0.013, min=0.002, med=0.011, max=0.134, p(90)=0.014, p(95)=0.020
- http_req_duration: avg=7.894, min=1.750, med=7.616, max=15.685, p(90)=11.616, p(95)=11.997, p(99)=14.351
