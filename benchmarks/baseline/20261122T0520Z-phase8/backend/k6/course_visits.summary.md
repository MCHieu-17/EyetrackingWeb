# k6 summary

scenario: course_visits

- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_blocked: avg=0.012, min=0.001, med=0.010, max=0.128, p(90)=0.014, p(95)=0.015, p(99)=0.111
- iterations: count=215.000, rate=21.388
- http_req_sending: p(90)=0.051, p(95)=0.064, p(99)=0.132, avg=0.038, min=0.005, med=0.040, max=0.162
- vus: max=5.000, min=5.000
- http_req_waiting: avg=32.137, min=10.980, med=28.254, max=88.257, p(90)=53.491, p(95)=55.545, p(99)=59.636
- http_req_duration: avg=32.357, min=11.080, med=28.575, max=88.409, p(90)=54.031, p(95)=55.648, p(99)=60.037
- http_req_duration{expected_response:true}: p(90)=54.031, p(95)=55.648, p(99)=60.037, avg=32.357, min=11.080, med=28.575, max=88.409
- http_req_receiving: p(95)=0.405, p(99)=0.633, avg=0.181, min=0.038, med=0.108, max=3.832, p(90)=0.355
- http_req_failed: rate=0.000
- http_req_connecting: max=0.084, p(90)=0.000, p(95)=0.000, p(99)=0.081, avg=0.002, min=0.000, med=0.000
