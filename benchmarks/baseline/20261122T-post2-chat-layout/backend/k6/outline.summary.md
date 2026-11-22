# k6 summary

scenario: outline

- http_req_duration: min=1.813, med=8.587, max=46.372, p(90)=13.055, p(95)=13.550, p(99)=34.088, avg=9.258
- http_req_failed: rate=0.000
- vus: min=5.000, max=5.000
- http_req_connecting: p(99)=0.501, avg=0.013, min=0.000, med=0.000, max=1.199, p(90)=0.000, p(95)=0.000
- http_req_sending: p(90)=0.051, p(95)=0.056, p(99)=0.854, avg=0.052, min=0.006, med=0.039, max=0.889
- http_req_waiting: med=8.354, max=46.313, p(90)=12.810, p(95)=13.227, p(99)=33.600, avg=9.028, min=1.761
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_receiving: avg=0.177, min=0.019, med=0.140, max=0.950, p(90)=0.340, p(95)=0.469, p(99)=0.858
- iterations: count=240.000, rate=23.583
- http_req_duration{expected_response:true}: p(90)=13.055, p(95)=13.550, p(99)=34.088, avg=9.258, min=1.813, med=8.587, max=46.372
- http_req_blocked: max=1.299, p(90)=0.013, p(95)=0.014, p(99)=1.272, avg=0.036, min=0.002, med=0.011
