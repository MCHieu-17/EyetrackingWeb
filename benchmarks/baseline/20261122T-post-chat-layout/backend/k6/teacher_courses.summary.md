# k6 summary

scenario: teacher_courses

- http_req_receiving: avg=0.110, min=0.014, med=0.100, max=0.478, p(90)=0.238, p(95)=0.314, p(99)=0.352
- http_req_connecting: p(95)=0.000, p(99)=0.071, avg=0.002, min=0.000, med=0.000, max=0.077, p(90)=0.000
- http_req_blocked: avg=0.014, min=0.003, med=0.011, max=0.108, p(90)=0.014, p(95)=0.019, p(99)=0.103
- http_req_duration{expected_response:true}: med=7.960, max=14.494, p(90)=12.459, p(95)=13.083, p(99)=14.106, avg=8.716, min=2.792
- http_req_sending: avg=0.041, min=0.011, med=0.042, max=0.077, p(90)=0.049, p(95)=0.052, p(99)=0.067
- vus: min=2.000, max=2.000
- http_req_duration: p(99)=14.106, avg=8.716, min=2.792, med=7.960, max=14.494, p(90)=12.459, p(95)=13.083
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- iterations: count=96.000, rate=9.538
- http_req_failed: rate=0.000
- http_req_waiting: max=14.224, p(90)=12.178, p(95)=12.837, p(99)=14.007, avg=8.566, min=2.702, med=7.711
