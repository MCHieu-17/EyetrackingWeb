# k6 summary

scenario: samples

- http_req_duration{expected_response:true}: avg=22.541, min=7.132, med=24.069, max=32.988, p(90)=30.819, p(95)=31.339, p(99)=32.658
- http_req_duration: med=24.069, max=32.988, p(90)=30.819, p(95)=31.339, p(99)=32.658, avg=22.541, min=7.132
- vus: min=1.000, max=1.000
- http_req_sending: p(95)=0.057, p(99)=0.058, avg=0.041, min=0.012, med=0.043, max=0.058, p(90)=0.051
- http_req_waiting: min=7.061, med=23.873, max=32.678, p(90)=30.635, p(95)=31.147, p(99)=32.372, avg=22.377
- http_req_blocked: med=0.011, max=0.140, p(90)=0.015, p(95)=0.043, p(99)=0.121, avg=0.018, min=0.003
- iterations: count=20.000, rate=4.472
- http_req_connecting: p(99)=0.079, avg=0.005, min=0.000, med=0.000, max=0.098, p(90)=0.000, p(95)=0.005
- http_req_failed: rate=0.000
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- http_req_receiving: p(90)=0.166, p(95)=0.202, p(99)=0.254, avg=0.124, min=0.059, med=0.119, max=0.267
