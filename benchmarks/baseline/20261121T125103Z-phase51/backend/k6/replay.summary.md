# k6 summary

scenario: replay

- http_req_duration{expected_response:true}: max=106.216, p(90)=53.838, p(95)=67.199, p(99)=80.211, avg=41.250, min=16.848, med=40.481
- iterations: count=84.000, rate=8.259
- http_req_failed: rate=0.000
- http_req_sending: avg=0.043, min=0.008, med=0.043, max=0.140, p(90)=0.055, p(95)=0.060, p(99)=0.092
- http_req_connecting: med=0.000, max=0.072, p(90)=0.000, p(95)=0.000, p(99)=0.068, avg=0.002, min=0.000
- http_req_waiting: min=16.778, med=40.346, max=106.044, p(90)=53.708, p(95)=66.929, p(99)=80.079, avg=41.095
- http_req_receiving: avg=0.111, min=0.050, med=0.096, max=0.631, p(90)=0.144, p(95)=0.184, p(99)=0.619
- http_req_blocked: p(99)=0.097, avg=0.014, min=0.003, med=0.011, max=0.102, p(90)=0.015, p(95)=0.017
- http_req_tls_handshaking: p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000
- http_req_duration: p(90)=53.838, p(95)=67.199, p(99)=80.211, avg=41.250, min=16.848, med=40.481, max=106.216
- vus: min=2.000, max=2.000
