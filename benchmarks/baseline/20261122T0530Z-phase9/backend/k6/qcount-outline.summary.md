# k6 summary

scenario: outline

- http_req_duration: med=9.149, max=10.403, p(90)=10.232, p(95)=10.290, p(99)=10.381, avg=8.140, min=1.973
- vus: min=1.000, max=1.000
- iterations: count=20.000, rate=4.780
- http_req_waiting: p(99)=10.198, avg=7.980, min=1.923, med=8.982, max=10.220, p(90)=10.024, p(95)=10.108
- http_req_failed: rate=0.000
- http_req_blocked: p(99)=0.139, avg=0.020, min=0.006, med=0.011, max=0.163, p(90)=0.021, p(95)=0.046
- http_req_sending: avg=0.044, min=0.014, med=0.041, max=0.144, p(90)=0.049, p(95)=0.054, p(99)=0.126
- http_req_receiving: avg=0.116, min=0.028, med=0.126, max=0.200, p(90)=0.178, p(95)=0.194, p(99)=0.199
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_duration{expected_response:true}: med=9.149, max=10.403, p(90)=10.232, p(95)=10.290, p(99)=10.381, avg=8.140, min=1.973
- http_req_connecting: max=0.121, p(90)=0.000, p(95)=0.006, p(99)=0.098, avg=0.006, min=0.000, med=0.000
