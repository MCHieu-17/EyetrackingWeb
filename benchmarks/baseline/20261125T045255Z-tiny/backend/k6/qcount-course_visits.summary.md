# k6 summary

scenario: course_visits

- http_req_sending: p(99)=0.054, avg=0.042, min=0.016, med=0.042, max=0.054, p(90)=0.052, p(95)=0.053
- http_req_connecting: max=0.081, p(90)=0.000, p(95)=0.004, p(99)=0.065, avg=0.004, min=0.000, med=0.000
- http_req_duration: p(90)=10.201, p(95)=10.438, p(99)=10.479, avg=7.879, min=2.312, med=7.525, max=10.490
- http_req_failed: rate=0.000
- vus: min=1.000, max=1.000
- http_req_receiving: p(90)=0.168, p(95)=0.178, p(99)=0.199, avg=0.098, min=0.028, med=0.095, max=0.204
- http_req_duration{expected_response:true}: avg=7.879, min=2.312, med=7.525, max=10.490, p(90)=10.201, p(95)=10.438, p(99)=10.479
- http_req_blocked: p(90)=0.015, p(95)=0.043, p(99)=0.097, avg=0.017, min=0.003, med=0.011, max=0.111
- http_req_waiting: avg=7.738, min=2.232, med=7.411, max=10.322, p(90)=10.016, p(95)=10.246, p(99)=10.307
- iterations: count=20.000, rate=4.787
- http_req_tls_handshaking: max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000
