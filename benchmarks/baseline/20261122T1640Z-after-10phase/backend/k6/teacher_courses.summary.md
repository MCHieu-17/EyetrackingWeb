# k6 summary

scenario: teacher_courses

- http_req_duration: p(90)=11.634, p(95)=12.764, p(99)=36.103, avg=8.654, min=2.472, med=8.072, max=36.103
- http_req_sending: avg=0.039, min=0.011, med=0.040, max=0.091, p(90)=0.049, p(95)=0.051, p(99)=0.079
- http_req_blocked: med=0.011, max=0.115, p(90)=0.014, p(95)=0.033, p(99)=0.115, avg=0.014, min=0.002
- http_req_connecting: avg=0.002, min=0.000, med=0.000, max=0.086, p(90)=0.000, p(95)=0.000, p(99)=0.085
- http_req_receiving: avg=0.117, min=0.024, med=0.104, max=0.335, p(90)=0.239, p(95)=0.255, p(99)=0.324
- http_req_failed: rate=0.000
- http_req_waiting: avg=8.498, min=2.414, med=7.812, max=36.016, p(90)=11.420, p(95)=12.630, p(99)=36.015
- iterations: count=96.000, rate=9.542
- vus: min=2.000, max=2.000
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- http_req_duration{expected_response:true}: p(90)=11.634, p(95)=12.764, p(99)=36.103, avg=8.654, min=2.472, med=8.072, max=36.103
