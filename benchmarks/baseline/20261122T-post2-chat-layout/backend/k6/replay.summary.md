# k6 summary

scenario: replay

- http_req_sending: avg=0.048, min=0.008, med=0.042, max=0.255, p(90)=0.067, p(95)=0.116, p(99)=0.171
- iterations: count=96.000, rate=9.496
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- http_req_waiting: avg=9.422, min=2.570, med=9.233, max=36.453, p(90)=12.552, p(95)=13.605, p(99)=35.308
- http_req_failed: rate=0.000
- http_req_duration: avg=9.625, min=2.630, med=9.509, max=36.597, p(90)=12.902, p(95)=13.853, p(99)=35.476
- http_req_duration{expected_response:true}: min=2.630, med=9.509, max=36.597, p(90)=12.902, p(95)=13.853, p(99)=35.476, avg=9.625
- http_req_blocked: max=0.388, p(90)=0.016, p(95)=0.031, p(99)=0.123, avg=0.017, min=0.003, med=0.011
- http_req_receiving: p(99)=0.449, avg=0.154, min=0.020, med=0.118, max=0.478, p(90)=0.327, p(95)=0.383
- http_req_connecting: p(90)=0.000, p(95)=0.000, p(99)=0.076, avg=0.002, min=0.000, med=0.000, max=0.078
- vus: min=2.000, max=2.000
