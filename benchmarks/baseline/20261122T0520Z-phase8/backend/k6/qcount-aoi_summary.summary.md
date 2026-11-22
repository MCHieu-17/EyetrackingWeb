# k6 summary

scenario: aoi_summary

- iterations: count=20.000, rate=2.543
- http_req_blocked: p(99)=0.081, avg=0.015, min=0.003, med=0.011, max=0.097, p(90)=0.013, p(95)=0.017
- http_req_connecting: p(99)=0.058, avg=0.004, min=0.000, med=0.000, max=0.071, p(90)=0.000, p(95)=0.004
- http_req_tls_handshaking: max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000
- http_req_receiving: p(99)=0.861, avg=0.273, min=0.106, med=0.198, max=0.915, p(90)=0.452, p(95)=0.643
- http_req_failed: rate=0.000
- http_req_duration{expected_response:true}: p(95)=226.923, p(99)=228.687, avg=192.214, min=170.356, med=190.983, max=229.128, p(90)=212.034
- vus: min=1.000, max=1.000
- http_req_sending: p(90)=0.088, p(95)=0.139, p(99)=0.155, avg=0.060, min=0.018, med=0.052, max=0.159
- http_req_waiting: p(95)=226.709, p(99)=228.464, avg=191.881, min=170.201, med=190.581, max=228.903, p(90)=211.564
- http_req_duration: max=229.128, p(90)=212.034, p(95)=226.923, p(99)=228.687, avg=192.214, min=170.356, med=190.983
