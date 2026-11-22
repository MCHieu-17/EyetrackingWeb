# k6 summary

scenario: outline

- http_req_sending: max=0.501, p(90)=0.051, p(95)=0.062, p(99)=0.095, avg=0.042, min=0.008, med=0.040
- http_req_failed: rate=0.000
- http_req_tls_handshaking: p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000
- iterations: count=240.000, rate=23.514
- http_req_blocked: min=0.002, med=0.011, max=0.127, p(90)=0.014, p(95)=0.032, p(99)=0.119, avg=0.014
- http_req_connecting: avg=0.002, min=0.000, med=0.000, max=0.092, p(90)=0.000, p(95)=0.000, p(99)=0.083
- vus: min=5.000, max=5.000
- http_req_duration: med=8.637, max=49.592, p(90)=13.005, p(95)=13.619, p(99)=16.124, avg=9.242, min=2.462
- http_req_duration{expected_response:true}: med=8.637, max=49.592, p(90)=13.005, p(95)=13.619, p(99)=16.124, avg=9.242, min=2.462
- http_req_receiving: p(90)=0.340, p(95)=0.412, p(99)=0.633, avg=0.174, min=0.024, med=0.135, max=0.794
- http_req_waiting: p(99)=15.970, avg=9.026, min=2.365, med=8.455, max=49.523, p(90)=12.706, p(95)=13.313
