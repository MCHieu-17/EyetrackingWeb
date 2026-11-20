# k6 summary

scenario: outline

- http_req_duration: p(99)=24.404, avg=13.870, min=2.558, med=15.436, max=28.755, p(90)=20.130, p(95)=20.950
- http_req_blocked: max=0.119, p(90)=0.014, p(95)=0.016, p(99)=0.117, avg=0.012, min=0.002, med=0.010
- http_req_connecting: max=0.081, p(90)=0.000, p(95)=0.000, p(99)=0.079, avg=0.002, min=0.000, med=0.000
- http_req_tls_handshaking: max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000
- http_req_failed: rate=0.000
- http_req_duration{expected_response:true}: avg=13.870, min=2.558, med=15.436, max=28.755, p(90)=20.130, p(95)=20.950, p(99)=24.404
- http_req_waiting: max=28.290, p(90)=19.973, p(95)=20.737, p(99)=23.527, avg=13.624, min=2.495, med=15.019
- http_req_sending: min=0.006, med=0.037, max=0.153, p(90)=0.052, p(95)=0.063, p(99)=0.086, avg=0.037
- iterations: count=235.000, rate=23.281
- vus: min=5.000, max=5.000
- http_req_receiving: avg=0.209, min=0.025, med=0.165, max=1.130, p(90)=0.418, p(95)=0.515, p(99)=0.909
