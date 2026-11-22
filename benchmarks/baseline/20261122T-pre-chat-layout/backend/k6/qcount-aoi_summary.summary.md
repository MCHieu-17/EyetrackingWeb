# k6 summary

scenario: aoi_summary

- iterations: count=20.000, rate=4.348
- http_req_waiting: avg=28.786, min=10.317, med=31.589, max=41.104, p(90)=35.764, p(95)=36.670, p(99)=40.217
- http_req_failed: rate=0.000
- http_req_connecting: avg=0.003, min=0.000, med=0.000, max=0.069, p(90)=0.000, p(95)=0.003, p(99)=0.056
- http_req_duration: p(95)=36.908, p(99)=40.382, avg=28.931, min=10.415, med=31.730, max=41.250, p(90)=35.909
- http_req_blocked: avg=0.017, min=0.004, med=0.012, max=0.098, p(90)=0.026, p(95)=0.034, p(99)=0.085
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- vus: min=1.000, max=1.000
- http_req_receiving: avg=0.087, min=0.047, med=0.077, max=0.185, p(90)=0.120, p(95)=0.177, p(99)=0.183
- http_req_sending: p(90)=0.069, p(95)=0.075, p(99)=0.077, avg=0.057, min=0.020, med=0.057, max=0.078
- http_req_duration{expected_response:true}: med=31.730, max=41.250, p(90)=35.909, p(95)=36.908, p(99)=40.382, avg=28.931, min=10.415
