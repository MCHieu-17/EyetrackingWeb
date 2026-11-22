# k6 summary

scenario: replay

- http_req_receiving: min=0.069, med=0.094, max=0.243, p(90)=0.151, p(95)=0.181, p(99)=0.231, avg=0.110
- http_req_failed: rate=0.000
- http_req_duration: max=72.526, p(90)=49.260, p(95)=64.204, p(99)=70.862, avg=42.881, min=30.280, med=40.903
- http_req_tls_handshaking: p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000
- iterations: rate=4.102, count=20.000
- vus: min=1.000, max=1.000
- http_req_connecting: max=0.074, p(90)=0.000, p(95)=0.004, p(99)=0.060, avg=0.004, min=0.000, med=0.000
- http_req_duration{expected_response:true}: min=30.280, med=40.903, max=72.526, p(90)=49.260, p(95)=64.204, p(99)=70.862, avg=42.881
- http_req_sending: p(90)=0.061, p(95)=0.067, p(99)=0.087, avg=0.046, min=0.013, med=0.042, max=0.092
- http_req_blocked: avg=0.017, min=0.004, med=0.012, max=0.107, p(90)=0.016, p(95)=0.026, p(99)=0.090
- http_req_waiting: med=40.762, max=72.402, p(90)=49.143, p(95)=64.037, p(99)=70.729, avg=42.725, min=30.165
