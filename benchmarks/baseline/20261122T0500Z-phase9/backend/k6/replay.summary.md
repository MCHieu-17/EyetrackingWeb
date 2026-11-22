# k6 summary

scenario: replay

- http_req_receiving: max=0.699, p(90)=0.351, p(95)=0.468, p(99)=0.602, avg=0.213, min=0.050, med=0.201
- http_req_duration: avg=15.488, min=4.419, med=16.238, max=50.255, p(90)=19.826, p(95)=22.221, p(99)=50.128
- http_req_waiting: avg=15.233, min=4.335, med=15.960, max=49.993, p(90)=19.498, p(95)=21.600, p(99)=49.985
- http_req_connecting: avg=0.002, min=0.000, med=0.000, max=0.082, p(90)=0.000, p(95)=0.000, p(99)=0.080
- http_req_duration{expected_response:true}: avg=15.488, min=4.419, med=16.238, max=50.255, p(90)=19.826, p(95)=22.221, p(99)=50.128
- vus: min=2.000, max=2.000
- http_req_blocked: p(90)=0.015, p(95)=0.017, p(99)=0.107, avg=0.013, min=0.003, med=0.011, max=0.109
- http_req_sending: min=0.011, med=0.042, max=0.090, p(90)=0.057, p(95)=0.062, p(99)=0.085, avg=0.042
- http_req_failed: rate=0.000
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- iterations: count=94.000, rate=9.239
