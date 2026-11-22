# k6 summary

scenario: course_students

- vus: max=5.000, min=5.000
- http_req_sending: max=0.402, p(90)=0.051, p(95)=0.055, p(99)=0.087, avg=0.042, min=0.007, med=0.041
- http_req_blocked: avg=0.017, min=0.002, med=0.011, max=0.521, p(90)=0.015, p(95)=0.026, p(99)=0.151
- http_req_waiting: p(99)=43.596, avg=9.541, min=2.874, med=7.658, max=45.531, p(90)=14.626, p(95)=15.421
- http_req_receiving: avg=0.205, min=0.026, med=0.114, max=2.128, p(90)=0.358, p(95)=0.413, p(99)=1.979
- http_req_connecting: max=0.476, p(90)=0.000, p(95)=0.000, p(99)=0.113, avg=0.004, min=0.000, med=0.000
- http_req_duration{expected_response:true}: p(99)=43.699, avg=9.788, min=2.962, med=7.764, max=45.646, p(90)=15.120, p(95)=15.869
- iterations: count=238.000, rate=23.677
- http_req_failed: rate=0.000
- http_req_tls_handshaking: p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000
- http_req_duration: avg=9.788, min=2.962, med=7.764, max=45.646, p(90)=15.120, p(95)=15.869, p(99)=43.699
