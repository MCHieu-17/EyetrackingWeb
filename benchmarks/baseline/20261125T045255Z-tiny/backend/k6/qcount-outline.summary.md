# k6 summary

scenario: outline

- http_req_connecting: avg=0.005, min=0.000, med=0.000, max=0.092, p(90)=0.000, p(95)=0.005, p(99)=0.075
- vus: min=1.000, max=1.000
- http_req_sending: med=0.042, max=0.821, p(90)=0.053, p(95)=0.111, p(99)=0.679, avg=0.081, min=0.017
- iterations: count=20.000, rate=4.802
- http_req_duration{expected_response:true}: p(95)=9.945, p(99)=10.792, avg=7.306, min=2.691, med=7.253, max=11.004, p(90)=9.526
- http_req_receiving: min=0.038, med=0.105, max=0.262, p(90)=0.157, p(95)=0.178, p(99)=0.246, avg=0.104
- http_req_waiting: avg=7.121, min=2.626, med=7.086, max=10.029, p(90)=9.232, p(95)=9.705, p(99)=9.964
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- http_req_duration: p(90)=9.526, p(95)=9.945, p(99)=10.792, avg=7.306, min=2.691, med=7.253, max=11.004
- http_req_failed: rate=0.000
- http_req_blocked: p(90)=0.018, p(95)=0.067, p(99)=0.112, avg=0.019, min=0.004, med=0.011, max=0.123
