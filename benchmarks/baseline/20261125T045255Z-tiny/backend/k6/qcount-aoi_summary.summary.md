# k6 summary

scenario: aoi_summary

- http_req_failed: rate=0.000
- http_req_duration: avg=25.110, min=12.507, med=25.712, max=36.518, p(90)=33.391, p(95)=33.614, p(99)=35.937
- http_req_waiting: p(95)=33.505, p(99)=35.813, avg=24.980, min=12.421, med=25.552, max=36.390, p(90)=33.279
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_receiving: p(95)=0.112, p(99)=0.123, avg=0.073, min=0.038, med=0.066, max=0.126, p(90)=0.108
- http_req_duration{expected_response:true}: avg=25.110, min=12.507, med=25.712, max=36.518, p(90)=33.391, p(95)=33.614, p(99)=35.937
- http_req_blocked: max=0.131, p(90)=0.013, p(95)=0.021, p(99)=0.109, avg=0.017, min=0.004, med=0.011
- iterations: count=20.000, rate=4.423
- http_req_connecting: avg=0.005, min=0.000, med=0.000, max=0.092, p(90)=0.000, p(95)=0.005, p(99)=0.074
- http_req_sending: avg=0.057, min=0.019, med=0.051, max=0.137, p(90)=0.077, p(95)=0.101, p(99)=0.130
- vus: min=1.000, max=1.000
