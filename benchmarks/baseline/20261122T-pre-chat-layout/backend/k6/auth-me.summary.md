# k6 summary

scenario: me

- http_req_connecting: p(99)=0.043, avg=0.002, min=0.000, med=0.000, max=0.082, p(90)=0.000, p(95)=0.000
- http_req_waiting: avg=7.355, min=1.895, med=8.299, max=10.443, p(90)=9.942, p(95)=10.058, p(99)=10.295
- http_req_blocked: p(95)=0.034, p(99)=0.133, avg=0.016, min=0.003, med=0.011, max=0.153, p(90)=0.015
- http_req_failed: rate=0.000
- vus: min=1.000, max=1.000
- http_req_duration{expected_response:true}: avg=7.484, min=1.952, med=8.444, max=10.679, p(90)=10.123, p(95)=10.222, p(99)=10.490
- http_req_sending: med=0.040, max=0.060, p(90)=0.046, p(95)=0.051, p(99)=0.058, avg=0.037, min=0.011
- http_req_duration: max=10.679, p(90)=10.123, p(95)=10.222, p(99)=10.490, avg=7.484, min=1.952, med=8.444
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_receiving: med=0.106, max=0.176, p(90)=0.134, p(95)=0.145, p(99)=0.168, avg=0.092, min=0.025
- iterations: count=48.000, rate=4.796
