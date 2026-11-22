# k6 summary

scenario: teacher_courses

- http_req_receiving: med=0.120, max=0.459, p(90)=0.210, p(95)=0.305, p(99)=0.429, avg=0.139, min=0.031
- http_req_connecting: p(95)=0.004, p(99)=0.072, avg=0.004, min=0.000, med=0.000, max=0.089, p(90)=0.000
- http_req_duration{expected_response:true}: min=3.064, med=11.641, max=21.797, p(90)=12.861, p(95)=13.377, p(99)=20.113, avg=11.230
- vus: min=1.000, max=1.000
- http_req_failed: rate=0.000
- http_req_tls_handshaking: p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000
- iterations: count=20.000, rate=4.710
- http_req_blocked: avg=0.017, min=0.006, med=0.011, max=0.118, p(90)=0.016, p(95)=0.022, p(99)=0.099
- http_req_sending: p(95)=0.053, p(99)=0.054, avg=0.044, min=0.027, med=0.043, max=0.054, p(90)=0.052
- http_req_duration: avg=11.230, min=3.064, med=11.641, max=21.797, p(90)=12.861, p(95)=13.377, p(99)=20.113
- http_req_waiting: p(90)=12.686, p(95)=13.222, p(99)=20.012, avg=11.047, min=2.990, med=11.467, max=21.709
