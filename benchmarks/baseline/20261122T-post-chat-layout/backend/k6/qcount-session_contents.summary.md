# k6 summary

scenario: session_contents

- http_req_failed: rate=0.000
- iterations: rate=4.708, count=20.000
- http_req_connecting: p(99)=0.072, avg=0.004, min=0.000, med=0.000, max=0.089, p(90)=0.000, p(95)=0.004
- http_req_sending: p(95)=0.054, p(99)=0.058, avg=0.041, min=0.012, med=0.042, max=0.059, p(90)=0.054
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- http_req_blocked: p(90)=0.017, p(95)=0.024, p(99)=0.104, avg=0.017, min=0.003, med=0.011, max=0.124
- vus: min=1.000, max=1.000
- http_req_duration: p(90)=15.360, p(95)=15.375, p(99)=15.404, avg=11.338, min=3.054, med=12.845, max=15.411
- http_req_receiving: p(90)=0.145, p(95)=0.149, p(99)=0.170, avg=0.113, min=0.039, med=0.121, max=0.176
- http_req_duration{expected_response:true}: p(90)=15.360, p(95)=15.375, p(99)=15.404, avg=11.338, min=3.054, med=12.845, max=15.411
- http_req_waiting: avg=11.184, min=2.999, med=12.645, max=15.266, p(90)=15.184, p(95)=15.197, p(99)=15.252
