# k6 summary

scenario: replay

- http_req_connecting: avg=0.006, min=0.000, med=0.000, max=0.126, p(90)=0.000, p(95)=0.006, p(99)=0.102
- http_req_duration{expected_response:true}: med=46.894, max=60.179, p(90)=56.592, p(95)=59.021, p(99)=59.947, avg=42.773, min=20.406
- http_req_duration: p(90)=56.592, p(95)=59.021, p(99)=59.947, avg=42.773, min=20.406, med=46.894, max=60.179
- http_req_failed: rate=0.000
- vus: max=1.000, min=1.000
- http_req_receiving: avg=0.121, min=0.067, med=0.113, max=0.201, p(90)=0.178, p(95)=0.188, p(99)=0.199
- http_req_sending: p(95)=0.099, p(99)=0.253, avg=0.058, min=0.011, med=0.044, max=0.291, p(90)=0.070
- http_req_waiting: p(99)=59.825, avg=42.594, min=20.270, med=46.717, max=60.062, p(90)=56.348, p(95)=58.878
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- http_req_blocked: avg=0.021, min=0.003, med=0.012, max=0.186, p(90)=0.018, p(95)=0.031, p(99)=0.155
- iterations: count=20.000, rate=4.100
