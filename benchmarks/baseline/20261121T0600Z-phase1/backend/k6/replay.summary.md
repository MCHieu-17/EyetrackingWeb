# k6 summary

scenario: replay

- vus: min=2.000, max=2.000
- http_req_duration: avg=48.967, min=19.381, med=53.258, max=94.018, p(90)=61.193, p(95)=63.948, p(99)=85.904
- http_req_blocked: max=0.140, p(90)=0.016, p(95)=0.023, p(99)=0.133, avg=0.015, min=0.002, med=0.011
- http_req_duration{expected_response:true}: avg=48.967, min=19.381, med=53.258, max=94.018, p(90)=61.193, p(95)=63.948, p(99)=85.904
- http_req_failed: rate=0.000
- iterations: count=82.000, rate=7.991
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_connecting: min=0.000, med=0.000, max=0.103, p(90)=0.000, p(95)=0.000, p(99)=0.100, avg=0.002
- http_req_receiving: p(99)=0.525, avg=0.132, min=0.050, med=0.103, max=1.162, p(90)=0.203, p(95)=0.222
- http_req_sending: p(99)=0.067, avg=0.040, min=0.008, med=0.042, max=0.071, p(90)=0.050, p(95)=0.053
- http_req_waiting: p(95)=63.836, p(99)=85.766, avg=48.795, min=19.278, med=53.099, max=93.854, p(90)=61.071
