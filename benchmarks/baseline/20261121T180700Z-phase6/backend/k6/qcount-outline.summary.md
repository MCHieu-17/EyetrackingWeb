# k6 summary

scenario: outline

- http_req_sending: avg=0.041, min=0.013, med=0.042, max=0.070, p(90)=0.060, p(95)=0.065, p(99)=0.069
- vus: min=1.000, max=1.000
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- http_req_waiting: avg=8.950, min=2.296, med=10.127, max=11.890, p(90)=11.494, p(95)=11.541, p(99)=11.820
- http_req_failed: rate=0.000
- http_req_receiving: max=0.213, p(90)=0.177, p(95)=0.202, p(99)=0.211, avg=0.117, min=0.038, med=0.112
- iterations: count=20.000, rate=4.758
- http_req_duration: p(90)=11.709, p(95)=11.753, p(99)=12.038, avg=9.108, min=2.351, med=10.319, max=12.109
- http_req_duration{expected_response:true}: p(95)=11.753, p(99)=12.038, avg=9.108, min=2.351, med=10.319, max=12.109, p(90)=11.709
- http_req_connecting: min=0.000, med=0.000, max=0.100, p(90)=0.000, p(95)=0.005, p(99)=0.081, avg=0.005
- http_req_blocked: avg=0.017, min=0.003, med=0.011, max=0.140, p(90)=0.013, p(95)=0.020, p(99)=0.116
