# k6 summary

scenario: replay

- http_req_blocked: min=0.003, med=0.011, max=0.122, p(90)=0.016, p(95)=0.020, p(99)=0.118, avg=0.014
- iterations: count=94.000, rate=9.307
- http_req_waiting: max=26.300, p(90)=22.075, p(95)=22.896, p(99)=23.809, avg=13.705, min=4.456, med=14.596
- http_req_duration: p(95)=23.148, p(99)=23.976, avg=13.915, min=4.532, med=15.052, max=26.522, p(90)=22.311
- http_req_failed: rate=0.000
- vus: min=2.000, max=2.000
- http_req_connecting: max=0.092, p(90)=0.000, p(95)=0.000, p(99)=0.089, avg=0.002, min=0.000, med=0.000
- http_req_duration{expected_response:true}: med=15.052, max=26.522, p(90)=22.311, p(95)=23.148, p(99)=23.976, avg=13.915, min=4.532
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_sending: min=0.012, med=0.042, max=0.155, p(90)=0.050, p(95)=0.058, p(99)=0.127, avg=0.044
- http_req_receiving: med=0.140, max=0.559, p(90)=0.307, p(95)=0.390, p(99)=0.491, avg=0.166, min=0.034
