# k6 summary

scenario: course_visits

- http_req_duration{expected_response:true}: p(99)=45.587, avg=37.029, min=16.385, med=42.822, max=45.616, p(90)=45.429, p(95)=45.470
- http_req_sending: max=0.529, p(90)=0.050, p(95)=0.075, p(99)=0.438, avg=0.068, min=0.031, med=0.043
- http_req_receiving: min=0.115, med=0.204, max=0.491, p(90)=0.355, p(95)=0.396, p(99)=0.472, avg=0.229
- http_req_duration: avg=37.029, min=16.385, med=42.822, max=45.616, p(90)=45.429, p(95)=45.470, p(99)=45.587
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_failed: rate=0.000
- iterations: count=20.000, rate=4.200
- vus: max=1.000, min=1.000
- http_req_blocked: med=0.011, max=0.160, p(90)=0.014, p(95)=0.023, p(99)=0.132, avg=0.019, min=0.009
- http_req_waiting: p(95)=45.205, p(99)=45.321, avg=36.732, min=16.213, med=42.409, max=45.350, p(90)=45.171
- http_req_connecting: med=0.000, max=0.115, p(90)=0.000, p(95)=0.006, p(99)=0.093, avg=0.006, min=0.000
