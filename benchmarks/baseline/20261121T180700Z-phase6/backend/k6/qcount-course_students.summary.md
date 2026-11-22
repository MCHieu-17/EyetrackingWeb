# k6 summary

scenario: course_students

- http_req_waiting: min=32.458, med=62.708, max=138.896, p(90)=84.937, p(95)=100.088, p(99)=131.135, avg=67.454
- http_req_receiving: p(90)=0.305, p(95)=0.383, p(99)=0.738, avg=0.207, min=0.088, med=0.162, max=0.826
- http_req_failed: rate=0.000
- iterations: count=20.000, rate=3.721
- http_req_duration{expected_response:true}: p(99)=131.396, avg=67.710, min=32.835, med=62.901, max=139.150, p(90)=85.138, p(95)=100.379
- http_req_connecting: p(90)=0.000, p(95)=0.009, p(99)=0.153, avg=0.009, min=0.000, med=0.000, max=0.189
- http_req_duration: p(95)=100.379, p(99)=131.396, avg=67.710, min=32.835, med=62.901, max=139.150, p(90)=85.138
- http_req_tls_handshaking: p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000
- http_req_blocked: med=0.011, max=0.262, p(90)=0.014, p(95)=0.027, p(99)=0.215, avg=0.024, min=0.005
- http_req_sending: p(95)=0.074, p(99)=0.076, avg=0.048, min=0.017, med=0.046, max=0.077, p(90)=0.062
- vus: min=1.000, max=1.000
