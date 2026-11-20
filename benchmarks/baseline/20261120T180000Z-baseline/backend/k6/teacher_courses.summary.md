# k6 summary

scenario: teacher_courses

- http_req_waiting: max=52.470, p(90)=44.756, p(95)=45.420, p(99)=52.466, avg=32.225, min=18.008, med=33.307
- iterations: count=86.000, rate=8.573
- http_req_sending: med=0.041, max=0.079, p(90)=0.051, p(95)=0.057, p(99)=0.074, avg=0.039, min=0.009
- http_req_failed: rate=0.000
- http_req_blocked: min=0.003, med=0.012, max=0.106, p(90)=0.014, p(95)=0.016, p(99)=0.095, avg=0.013
- vus: min=2.000, max=2.000
- http_req_connecting: min=0.000, med=0.000, max=0.080, p(90)=0.000, p(95)=0.000, p(99)=0.071, avg=0.002
- http_req_duration{expected_response:true}: p(99)=52.543, avg=32.319, min=18.062, med=33.415, max=52.558, p(90)=44.873, p(95)=45.513
- http_req_duration: max=52.558, p(90)=44.873, p(95)=45.513, p(99)=52.543, avg=32.319, min=18.062, med=33.415
- http_req_tls_handshaking: max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000
- http_req_receiving: p(90)=0.071, p(95)=0.084, p(99)=0.097, avg=0.055, min=0.029, med=0.052, max=0.126
