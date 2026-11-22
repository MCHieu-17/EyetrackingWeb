# k6 summary

scenario: samples

- http_req_failed: rate=0.000
- iterations: count=20.000, rate=4.471
- http_req_duration{expected_response:true}: p(90)=27.715, p(95)=30.202, p(99)=42.092, avg=22.637, min=8.216, med=24.035, max=45.065
- vus: min=1.000, max=1.000
- http_req_blocked: p(99)=0.145, avg=0.019, min=0.003, med=0.011, max=0.173, p(90)=0.016, p(95)=0.031
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- http_req_sending: avg=0.043, min=0.011, med=0.043, max=0.087, p(90)=0.058, p(95)=0.061, p(99)=0.082
- http_req_duration: avg=22.637, min=8.216, med=24.035, max=45.065, p(90)=27.715, p(95)=30.202, p(99)=42.092
- http_req_waiting: p(90)=27.560, p(95)=30.032, p(99)=41.974, avg=22.485, min=7.993, med=23.882, max=44.960
- http_req_receiving: avg=0.109, min=0.059, med=0.094, max=0.210, p(90)=0.165, p(95)=0.193, p(99)=0.207
- http_req_connecting: avg=0.006, min=0.000, med=0.000, max=0.114, p(90)=0.000, p(95)=0.006, p(99)=0.092
