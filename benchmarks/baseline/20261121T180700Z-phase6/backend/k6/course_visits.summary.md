# k6 summary

scenario: course_visits

- http_req_duration: avg=34.314, min=13.570, med=28.878, max=74.525, p(90)=60.099, p(95)=64.802, p(99)=70.096
- vus: min=5.000, max=5.000
- http_req_receiving: min=0.037, med=0.110, max=0.542, p(90)=0.245, p(95)=0.351, p(99)=0.500, avg=0.138
- iterations: count=215.000, rate=21.227
- http_req_connecting: max=0.082, p(90)=0.000, p(95)=0.000, p(99)=0.074, avg=0.002, min=0.000, med=0.000
- http_req_failed: rate=0.000
- http_req_duration{expected_response:true}: min=13.570, med=28.878, max=74.525, p(90)=60.099, p(95)=64.802, p(99)=70.096, avg=34.314
- http_req_blocked: p(95)=0.016, p(99)=0.098, avg=0.011, min=0.002, med=0.010, max=0.116, p(90)=0.014
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_sending: p(90)=0.052, p(95)=0.057, p(99)=0.094, avg=0.036, min=0.007, med=0.039, max=0.159
- http_req_waiting: med=28.585, max=74.415, p(90)=60.002, p(95)=64.443, p(99)=69.652, avg=34.140, min=13.459
