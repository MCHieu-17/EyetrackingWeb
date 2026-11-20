# k6 summary

scenario: course_visits

- http_req_blocked: avg=0.012, min=0.001, med=0.010, max=0.130, p(90)=0.013, p(95)=0.015, p(99)=0.120
- http_req_tls_handshaking: p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000
- http_req_duration: max=78.811, p(90)=49.148, p(95)=70.752, p(99)=76.402, avg=37.592, min=16.661, med=35.584
- http_req_receiving: avg=0.240, min=0.048, med=0.130, max=2.910, p(90)=0.341, p(95)=0.495, p(99)=2.148
- http_req_sending: avg=0.039, min=0.004, med=0.038, max=0.635, p(90)=0.051, p(95)=0.056, p(99)=0.153
- vus: min=5.000, max=5.000
- http_req_duration{expected_response:true}: p(95)=70.752, p(99)=76.402, avg=37.592, min=16.661, med=35.584, max=78.811, p(90)=49.148
- http_req_connecting: min=0.000, med=0.000, max=0.098, p(90)=0.000, p(95)=0.000, p(99)=0.092, avg=0.002
- iterations: count=212.000, rate=20.725
- http_req_waiting: max=78.636, p(90)=48.792, p(95)=70.552, p(99)=76.104, avg=37.313, min=15.912, med=35.385
- http_req_failed: rate=0.000
