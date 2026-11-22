# k6 summary

scenario: teacher_courses

- http_req_receiving: p(99)=0.337, avg=0.121, min=0.029, med=0.104, max=0.342, p(90)=0.265, p(95)=0.317
- http_req_blocked: max=0.115, p(90)=0.018, p(95)=0.031, p(99)=0.098, avg=0.017, min=0.003, med=0.011
- http_req_duration: med=7.912, max=13.285, p(90)=12.036, p(95)=12.170, p(99)=13.062, avg=8.588, min=2.606
- http_req_duration{expected_response:true}: p(99)=13.062, avg=8.588, min=2.606, med=7.912, max=13.285, p(90)=12.036, p(95)=12.170
- http_req_waiting: p(95)=11.937, p(99)=12.867, avg=8.427, min=2.545, med=7.680, max=13.100, p(90)=11.870
- http_req_connecting: p(95)=0.004, p(99)=0.070, avg=0.004, min=0.000, med=0.000, max=0.086, p(90)=0.000
- vus: min=1.000, max=1.000
- http_req_sending: avg=0.041, min=0.012, med=0.040, max=0.061, p(90)=0.057, p(95)=0.057, p(99)=0.060
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- http_req_failed: rate=0.000
- iterations: count=20.000, rate=4.766
