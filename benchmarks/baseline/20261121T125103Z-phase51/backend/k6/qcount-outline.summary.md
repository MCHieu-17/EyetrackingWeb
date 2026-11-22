# k6 summary

scenario: outline

- http_req_connecting: min=0.000, med=0.000, max=0.075, p(90)=0.000, p(95)=0.004, p(99)=0.060, avg=0.004
- http_req_receiving: avg=0.113, min=0.034, med=0.132, max=0.245, p(90)=0.175, p(95)=0.180, p(99)=0.232
- iterations: count=20.000, rate=4.765
- http_req_failed: rate=0.000
- http_req_duration: min=2.399, med=10.357, max=12.098, p(90)=11.365, p(95)=11.530, p(99)=11.985, avg=8.699
- http_req_duration{expected_response:true}: avg=8.699, min=2.399, med=10.357, max=12.098, p(90)=11.365, p(95)=11.530, p(99)=11.985
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_waiting: avg=8.531, min=2.350, med=10.151, max=11.881, p(90)=11.126, p(95)=11.343, p(99)=11.773
- http_req_blocked: p(95)=0.020, p(99)=0.093, avg=0.016, min=0.004, med=0.011, max=0.111, p(90)=0.014
- http_req_sending: p(90)=0.050, p(95)=0.067, p(99)=0.284, avg=0.055, min=0.013, med=0.042, max=0.339
- vus: max=1.000, min=1.000
