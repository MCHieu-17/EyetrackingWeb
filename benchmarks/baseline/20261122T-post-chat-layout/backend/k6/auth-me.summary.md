# k6 summary

scenario: me

- http_req_duration: max=10.356, p(90)=9.688, p(95)=9.960, p(99)=10.348, avg=7.382, min=1.904, med=8.262
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_receiving: avg=0.102, min=0.025, med=0.104, max=0.324, p(90)=0.168, p(95)=0.175, p(99)=0.271
- vus: min=1.000, max=1.000
- http_req_failed: rate=0.000
- http_req_waiting: min=1.855, med=8.054, max=10.207, p(90)=9.532, p(95)=9.776, p(99)=10.199, avg=7.234
- http_req_duration{expected_response:true}: p(90)=9.688, p(95)=9.960, p(99)=10.348, avg=7.382, min=1.904, med=8.262, max=10.356
- http_req_connecting: max=0.081, p(90)=0.000, p(95)=0.000, p(99)=0.043, avg=0.002, min=0.000, med=0.000
- iterations: count=48.000, rate=4.798
- http_req_blocked: p(90)=0.013, p(95)=0.017, p(99)=0.140, avg=0.016, min=0.003, med=0.011, max=0.244
- http_req_sending: min=0.012, med=0.042, max=0.177, p(90)=0.062, p(95)=0.070, p(99)=0.171, avg=0.047
