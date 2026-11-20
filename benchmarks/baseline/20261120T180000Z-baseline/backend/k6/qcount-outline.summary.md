# k6 summary

scenario: outline

- http_req_tls_handshaking: p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000
- http_req_duration: max=13.346, p(90)=12.402, p(95)=12.847, p(99)=13.246, avg=10.108, min=2.766, med=11.476
- iterations: count=20.000, rate=4.731
- http_req_duration{expected_response:true}: med=11.476, max=13.346, p(90)=12.402, p(95)=12.847, p(99)=13.246, avg=10.108, min=2.766
- vus: min=1.000, max=1.000
- http_req_failed: rate=0.000
- http_req_connecting: med=0.000, max=0.074, p(90)=0.000, p(95)=0.004, p(99)=0.060, avg=0.004, min=0.000
- http_req_blocked: avg=0.015, min=0.004, med=0.012, max=0.104, p(90)=0.013, p(95)=0.022, p(99)=0.088
- http_req_receiving: avg=0.190, min=0.050, med=0.202, max=0.340, p(90)=0.263, p(95)=0.336, p(99)=0.339
- http_req_waiting: p(99)=12.950, avg=9.878, min=2.704, med=11.203, max=13.046, p(90)=12.201, p(95)=12.564
- http_req_sending: p(95)=0.054, p(99)=0.058, avg=0.040, min=0.012, med=0.042, max=0.059, p(90)=0.052
