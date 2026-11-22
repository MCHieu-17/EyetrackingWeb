# k6 summary

scenario: outline

- http_req_blocked: avg=0.016, min=0.004, med=0.011, max=0.113, p(90)=0.013, p(95)=0.019, p(99)=0.094
- vus: min=1.000, max=1.000
- http_req_connecting: p(90)=0.000, p(95)=0.004, p(99)=0.066, avg=0.004, min=0.000, med=0.000, max=0.081
- http_req_duration{expected_response:true}: p(99)=15.359, avg=10.990, min=2.750, med=11.333, max=15.446, p(90)=14.692, p(95)=15.011
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_duration: min=2.750, med=11.333, max=15.446, p(90)=14.692, p(95)=15.011, p(99)=15.359, avg=10.990
- http_req_receiving: max=0.888, p(90)=0.287, p(95)=0.393, p(99)=0.789, avg=0.180, min=0.036, med=0.136
- iterations: count=20.000, rate=4.714
- http_req_failed: rate=0.000
- http_req_waiting: p(99)=15.169, avg=10.770, min=2.698, med=11.105, max=15.287, p(90)=14.439, p(95)=14.700
- http_req_sending: min=0.014, med=0.041, max=0.050, p(90)=0.048, p(95)=0.048, p(99)=0.050, avg=0.040
