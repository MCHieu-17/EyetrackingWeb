# k6 summary

scenario: course_students

- http_req_connecting: min=0.000, med=0.000, max=0.103, p(90)=0.000, p(95)=0.000, p(99)=0.103, avg=0.002
- http_req_receiving: p(99)=0.634, avg=0.163, min=0.011, med=0.121, max=0.666, p(90)=0.351, p(95)=0.435
- http_req_duration{expected_response:true}: p(95)=12.250, p(99)=15.847, avg=7.941, min=1.862, med=7.560, max=19.171, p(90)=11.862
- http_req_sending: max=0.095, p(90)=0.050, p(95)=0.054, p(99)=0.074, avg=0.040, min=0.009, med=0.040
- http_req_duration: p(95)=12.250, p(99)=15.847, avg=7.941, min=1.862, med=7.560, max=19.171, p(90)=11.862
- iterations: count=243.000, rate=23.865
- http_req_waiting: med=7.360, max=19.092, p(90)=11.507, p(95)=11.884, p(99)=15.619, avg=7.738, min=1.812
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- vus: min=5.000, max=5.000
- http_req_blocked: p(90)=0.014, p(95)=0.015, p(99)=0.134, avg=0.014, min=0.003, med=0.011, max=0.203
- http_req_failed: rate=0.000
